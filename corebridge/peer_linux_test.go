package main

import (
	"context"
	"io"
	"net"
	"os"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
)

func TestRootPeerMatchesExactEstablishedConnection(t *testing.T) {
	local := "0100007F:CAFE"
	remote := "0100007F:4664"
	row := " 0: " + remote + " " + local + " 01 00000000:00000000 00:00000000 00000000 0 0 12345"
	if !rootPeerInTable(row, local, remote) {
		t.Fatal("root-owned established peer rejected")
	}
	for _, table := range []string{
		" 0: " + remote + " " + local + " 01 0 0 0 1001 0 12345",
		" 0: " + remote + " " + local + " 0A 0 0 0 0 0 12345",
		" 0: " + remote + " 0100007F:BEEF 01 0 0 0 0 0 12345",
		" 0: " + local + " " + remote + " 01 0 0 0 0 0 12345",
		" 0: " + remote + " " + local + " 01 0 0 0 invalid 0 12345",
		"",
	} {
		if rootPeerInTable(table, local, remote) {
			t.Fatal("untrusted or unmatched peer accepted")
		}
	}
}

func TestImpersonatedServiceReceivesNoBytesOrBearer(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("requires an unprivileged fake service")
	}
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	received := make(chan []byte, 4)
	go func() {
		for {
			connection, err := listener.Accept()
			if err != nil {
				return
			}
			connection.SetReadDeadline(time.Now().Add(time.Second))
			data, _ := io.ReadAll(connection)
			connection.Close()
			received <- data
		}
	}()
	client, err := grpc.NewClient(listener.Addr().String(),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithContextDialer(authenticatedDial),
		grpc.WithDefaultCallOptions(grpc.ForceCodec(rawCodec{})))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 250*time.Millisecond)
	defer cancel()
	ctx = metadata.NewOutgoingContext(ctx, metadata.Pairs("x-hiddify-secret", "fixture-private-bearer"))
	var response []byte
	if client.Invoke(ctx, "/hcore.Core/GetSystemInfo", []byte{}, &response) == nil {
		t.Fatal("unprivileged service accepted")
	}
	select {
	case data := <-received:
		if len(data) != 0 {
			t.Fatal("data sent before peer authentication")
		}
	case <-time.After(time.Second):
		t.Fatal("test never connected to the fake service")
	}
}
