package main
import (
 "testing"
 "google.golang.org/protobuf/encoding/protowire"
)
func TestGroupsWire(t *testing.T) {
 node:=field(nil,1,"<img src=\"https://example.invalid\">")
 node=protowire.AppendTag(node,4,protowire.VarintType);node=protowire.AppendVarint(node,42)
 group:=field(nil,1,"select");group=field(group,3,"chosen")
 group=protowire.AppendTag(group,4,protowire.VarintType);group=protowire.AppendVarint(group,1)
 group=protowire.AppendTag(group,6,protowire.BytesType);group=protowire.AppendBytes(group,node)
 data:=protowire.AppendTag(nil,1,protowire.BytesType);data=protowire.AppendBytes(data,group)
 result,err:=groups(data)
 if err!=nil||len(result)!=1||result[0].Name!="select"||len(result[0].Options)!=1 {t.Fatal("groups decode failed")}
 if result[0].Delays[result[0].Options[0]]!=42 {t.Fatal("delay decode failed")}
}
func TestInvalidWire(t *testing.T) {
 for _,b:=range [][]byte{{0xff},{0x0a,0xff},{0x08,0x80}} {
  if _,_,err:=fields(b);err==nil {t.Fatal("malformed protobuf accepted")}
 }
}
