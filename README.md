# Proton VPN for Omarchy

Official `protonvpn` CLI, driven from an Omarchy Quattro bar widget. Map,
country/city picker, Kill Switch, NetShield, Always On, split tunneling,
port forwarding, and traffic. Password and 2FA still go to Proton's own
TTY prompt — this plugin never sees them.

## Install

```bash
omarchy plugin add https://github.com/iamfitsum/omarchy-proton-vpn.git --enable
```

That clones this repo into `~/.config/omarchy/plugins/io.github.iamfitsum.omarchy-proton-vpn`,
validates the manifest, and enables the bar widget. Click the Proton mark.
The panel installs `proton-vpn-cli` if it is missing, then walks you through
sign-in.

Local checkout of this repo:

```bash
omarchy plugin add /path/to/proton-vpn --enable
omarchy bar move io.github.iamfitsum.omarchy-proton-vpn --after omarchy.network
```

Requires Omarchy Quattro. A free Proton account works; Plus unlocks country
targeting, P2P, Secure Core, Tor, NetShield ads/trackers, and port forwarding.

## Update

```bash
omarchy plugin update io.github.iamfitsum.omarchy-proton-vpn
```

## Remove

```bash
omarchy plugin remove io.github.iamfitsum.omarchy-proton-vpn
```

That does not uninstall the CLI or sign you out, and it does not fold the
keyring. Proton may write raw newlines back into
`~/.local/share/keyrings/Default_keyring.keyring`; if gnome-keyring then
says the file is unrecognized, sign in once from the panel (or run
`python3 sanitize_keyring.py --persist` from a checkout) before reboot.

```bash
protonvpn disconnect
protonvpn signout
omarchy pkg drop proton-vpn-cli
```

## Use

| Action | Effect |
|---|---|
| Left-click | Open the panel |
| Right-click | Connect fastest / disconnect |
| Middle-click | Refresh |

**Free plan:** Fastest, Random, and Change server (other free exits). The
CLI itself will not take a server name or `--random` on free; the panel
hops through Proton's session API the same way the desktop app does.

**Plus:** country → city drill, P2P / Secure Core / Tor, NetShield
ads+trackers, port forwarding on a P2P server.

The map is offline (Natural Earth + Proton's local server cache). No geo-IP.

Do **not** also install `proton-vpn-gtk-app`. CLI and GUI refuse to run
together. The panel warns if the app is present.

## Settings

Omarchy widget settings: nmcli link watch, desktop notifications. The bar
icon follows NetworkManager; `protonvpn status` runs while the panel is
open, after an action, and when the tunnel goes up or down — not on a
background timer. gnome-keyring 50 aborts if that CLI is polled forever.

## Session

Sign in once from the panel. The plugin folds Proton's gnome-keyring INI
so the session survives reboot until you sign out. Proton's daemon
sometimes writes raw newlines back; the plugin folds again about once a
minute while signed in, or while the account probe is timed out.

## Layout

```
manifest.json     plugin contract (id: io.github.iamfitsum.omarchy-proton-vpn)
Panel.qml         bar-widget entry (same pattern as omarchy.network)
Service.qml       CLI / nmcli / settings
WorldMap.qml      offline city map
Traffic.qml       tunnel sparkline
servers.py        cities from ~/.cache/Proton/VPN/serverlist.json
change.py         Change server / Random / named reconnect via the session API
apps.py           split-tunnel app picker
port.py           NAT-PMP renew on 10.2.0.1
sanitize_keyring.py  keep Proton signed in across reboot
```

```bash
python3 -m unittest discover -s tests -v
omarchy plugin validate .
```

## Credits

Panel, map, protections, and CLI glue were adapted from
[OmaProton VPN](https://github.com/grichard99/omaproton-vpn) (MIT).
World outline: [Natural Earth](https://www.naturalearthdata.com/) (public
domain). Proton mark: [Simple Icons](https://simpleicons.org) (CC0).
Not affiliated with Proton AG.

## License

[MIT](LICENSE)
