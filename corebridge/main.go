// Local-only Hiddify core bridge. Wire fields follow Hiddify's hcore.proto.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/protobuf/encoding/protowire"
	"io"
	"os"
	"strings"
	"time"
)

type rawCodec struct{}

func (rawCodec) Name() string                  { return "proto" }
func (rawCodec) Marshal(v any) ([]byte, error) { return v.([]byte), nil }
func (rawCodec) Unmarshal(data []byte, v any) error {
	*v.(*[]byte) = append([]byte(nil), data...)
	return nil
}
func field(b []byte, n protowire.Number, s string) []byte {
	b = protowire.AppendTag(b, n, protowire.BytesType)
	return protowire.AppendString(b, s)
}
func fields(data []byte) (map[int][][]byte, map[int]uint64, error) {
	texts := map[int][][]byte{}
	nums := map[int]uint64{}
	for len(data) > 0 {
		n, t, k := protowire.ConsumeTag(data)
		if k < 0 {
			return nil, nil, errors.New("wire")
		}
		data = data[k:]
		switch t {
		case protowire.BytesType:
			v, k := protowire.ConsumeBytes(data)
			if k < 0 {
				return nil, nil, errors.New("wire")
			}
			texts[int(n)] = append(texts[int(n)], v)
			data = data[k:]
		case protowire.VarintType:
			v, k := protowire.ConsumeVarint(data)
			if k < 0 {
				return nil, nil, errors.New("wire")
			}
			nums[int(n)] = v
			data = data[k:]
		default:
			k := protowire.ConsumeFieldValue(n, t, data)
			if k < 0 {
				return nil, nil, errors.New("wire")
			}
			data = data[k:]
		}
	}
	return texts, nums, nil
}
func text(f map[int][][]byte, n int) string {
	if len(f[n]) == 0 {
		return ""
	}
	s := string(f[n][0])
	if len(s) > 512 {
		return ""
	}
	return s
}

type Group struct {
	Name    string           `json:"name"`
	Now     string           `json:"now"`
	Options []string         `json:"options"`
	Delays  map[string]int64 `json:"delays"`
}

func groups(data []byte) ([]Group, error) {
	f, _, err := fields(data)
	if err != nil {
		return nil, err
	}
	result := []Group{}
	if len(f[1]) > 1000 {
		return nil, errors.New("limit")
	}
	for _, raw := range f[1] {
		g, n, err := fields(raw)
		if err != nil {
			return nil, err
		}
		if n[4] == 0 {
			continue
		}
		item := Group{Name: text(g, 1), Now: text(g, 3), Options: []string{}, Delays: map[string]int64{}}
		if len(g[6]) > 10000 {
			return nil, errors.New("limit")
		}
		for _, rawNode := range g[6] {
			node, nums, err := fields(rawNode)
			if err != nil {
				return nil, err
			}
			name := text(node, 1)
			if name != "" {
				item.Options = append(item.Options, name)
				item.Delays[name] = int64(nums[4])
			}
		}
		if item.Name != "" && len(result) < 32 {
			result = append(result, item)
		}
	}
	return result, nil
}
func firstMessage(ctx context.Context, conn *grpc.ClientConn, method string) ([]byte, error) {
	stream, err := conn.NewStream(ctx, &grpc.StreamDesc{ServerStreams: true}, method)
	if err != nil {
		return nil, err
	}
	if err := stream.SendMsg([]byte{}); err != nil {
		return nil, err
	}
	if err := stream.CloseSend(); err != nil {
		return nil, err
	}
	var data []byte
	if err := stream.RecvMsg(&data); err != nil {
		return nil, err
	}
	return data, nil
}

func perform() (any, error) {
	var req struct {
		Action string `json:"action"`
		Group  string `json:"group"`
		Name   string `json:"name"`
	}
	if err := json.NewDecoder(io.LimitReader(os.Stdin, 16384)).Decode(&req); err != nil {
		return nil, err
	}
	secret, err := os.ReadFile("/var/lib/hiddify-admin-bgservice/control.secret")
	if err != nil {
		return nil, err
	}
	if len(secret) < 32 || len(secret) > 8192 {
		return nil, errors.New("secret")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	ctx = metadata.NewOutgoingContext(ctx, metadata.Pairs("x-hiddify-secret", strings.TrimSpace(string(secret))))
	conn, err := grpc.NewClient("127.0.0.1:18020", grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithContextDialer(authenticatedDial), grpc.WithDefaultCallOptions(grpc.ForceCodec(rawCodec{}), grpc.MaxCallRecvMsgSize(8*1024*1024)))
	if err != nil {
		return nil, err
	}
	defer conn.Close()
	if req.Action == "groups" || req.Action == "status" {
		data, err := firstMessage(ctx, conn, "/hcore.Core/CoreInfoListener")
		if err != nil {
			return nil, err
		}
		_, values, err := fields(data)
		if err != nil {
			return nil, err
		}
		state := values[1]
		if req.Action == "status" {
			return map[string]any{"state": state}, nil
		}
		if state == 0 || state == 3 {
			return []Group{}, nil
		}
		data, err = firstMessage(ctx, conn, "/hcore.Core/MainOutboundsInfo")
		if err != nil {
			return nil, err
		}
		return groups(data)
	}
	if req.Action != "select" && req.Action != "test" {
		return nil, errors.New("action")
	}
	if len(req.Group) > 512 || len(req.Name) > 512 {
		return nil, errors.New("limit")
	}
	method := "/hcore.Core/SelectOutbound"
	data := field(nil, 1, req.Group)
	if req.Action == "select" {
		data = field(data, 2, req.Name)
	} else {
		method = "/hcore.Core/UrlTest"
	}
	var out []byte
	if err = conn.Invoke(ctx, method, data, &out); err != nil {
		return nil, err
	}
	_, n, err := fields(out)
	if err != nil || n[1] != 0 {
		return nil, errors.New("rejected")
	}
	return true, nil
}
func main() {
	result, err := perform()
	// Do not include raw errors: they may contain private hostnames or service credentials.
	if err != nil {
		json.NewEncoder(os.Stdout).Encode(map[string]any{"ok": false})
		return
	}
	json.NewEncoder(os.Stdout).Encode(map[string]any{"ok": true, "result": result})
}
