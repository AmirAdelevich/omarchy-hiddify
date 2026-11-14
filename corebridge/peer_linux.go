package main

import (
	"context"
	"encoding/binary"
	"errors"
	"fmt"
	"net"
	"os"
	"strconv"
	"strings"
)

// Authenticate the peer of this exact connected socket before gRPC can write
// authorization metadata. Checking a listening port before connecting races
// with another account rebinding that port. An established reverse tuple is
// owned by the kernel UID in /proc/net/tcp and cannot be replaced on this conn.
func authenticatedDial(ctx context.Context, address string) (net.Conn, error) {
	host, _, err := net.SplitHostPort(address)
	if err != nil || host != "127.0.0.1" {
		return nil, errors.New("unexpected service address")
	}
	connection, err := (&net.Dialer{}).DialContext(ctx, "tcp4", address)
	if err != nil {
		return nil, err
	}
	if err := verifyRootPeer(connection); err != nil {
		connection.Close()
		return nil, err
	}
	return connection, nil
}

func socketAddress(address net.Addr) (string, error) {
	tcp, ok := address.(*net.TCPAddr)
	if !ok || tcp.IP.To4() == nil || !tcp.IP.IsLoopback() {
		return "", errors.New("expected IPv4 loopback socket")
	}
	ip := binary.LittleEndian.Uint32(tcp.IP.To4())
	return fmt.Sprintf("%08X:%04X", ip, tcp.Port), nil
}

func rootPeerInTable(table, local, remote string) bool {
	for _, line := range strings.Split(table, "\n") {
		columns := strings.Fields(line)
		if len(columns) < 10 || columns[1] != remote || columns[2] != local || columns[3] != "01" {
			continue
		}
		uid, err := strconv.ParseUint(columns[7], 10, 32)
		return err == nil && uid == 0
	}
	return false
}

func verifyRootPeer(connection net.Conn) error {
	local, err := socketAddress(connection.LocalAddr())
	if err != nil {
		return err
	}
	remote, err := socketAddress(connection.RemoteAddr())
	if err != nil {
		return err
	}
	table, err := os.ReadFile("/proc/net/tcp")
	if err != nil || !rootPeerInTable(string(table), local, remote) {
		return errors.New("VPN service peer is not authenticated as root")
	}
	return nil
}
