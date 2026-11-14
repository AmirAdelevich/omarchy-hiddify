#!/usr/bin/env python3
"""Keep Hiddify running while moving its windows into or out of a hidden workspace."""
import json
import subprocess
import sys


def hypr_json(command):
    result = subprocess.run(['hyprctl', command, '-j'], check=True, capture_output=True, text=True, timeout=3)
    return json.loads(result.stdout)


def dispatch(command, argument):
    result = subprocess.run(['hyprctl', 'dispatch', command, argument],
                            capture_output=True, timeout=3)
    if result.returncode:
        if command == 'movetoworkspacesilent':
            workspace, window = argument.split(',', 1)
            code = 'hl.dispatch(hl.dsp.window.move({workspace=' + json.dumps(workspace) + ',follow=false,window=' + json.dumps(window) + '}))'
        else:
            code = 'hl.dispatch(hl.dsp.focus({window=' + json.dumps(argument) + '}))'
        subprocess.run(['hyprctl', 'eval', code], check=True, capture_output=True, timeout=3)


def main(action):
    clients = [client for client in hypr_json('clients')
               if client.get('class') == 'app.hiddify.com' and client.get('mapped')]
    workspace = 'special:hiddify-minimized'
    if action == 'restore':
        workspace = str(int(hypr_json('activeworkspace')['id']))
        clients = [client for client in clients
                   if client.get('workspace', {}).get('name') in ('special:hiddify-minimized', 'special:omarchy-hiddify')]
    for client in clients:
        address = client.get('address', '')
        if not address.startswith('0x') or any(c not in '0123456789abcdefABCDEF' for c in address[2:]):
            continue
        dispatch('movetoworkspacesilent', workspace + ',address:' + address)
        if action == 'restore':
            dispatch('focuswindow', 'address:' + address)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('minimize', 'restore'):
        raise SystemExit(2)
    main(sys.argv[1])
