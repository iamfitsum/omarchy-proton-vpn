# Security

This plugin runs unsandboxed inside `omarchy-shell`, like every Omarchy
plugin. It:

- stores no credentials, tokens, or account data
- never sees your Proton password or 2FA code (those go to the CLI TTY)
- makes no network requests of its own except NAT-PMP to the VPN gateway
  `10.2.0.1` while port forwarding is on
- never asks for root; CLI install uses Omarchy's installer terminal
- runs commands as argv lists, except the sign-in username which is
  allow-listed and single-quoted before it reaches the terminal launcher
- writes `~/.local/state/iamfitsum-proton-vpn/` (recents, Always On, nudge) and,
  only if you change split tunneling, `features.split_tunneling` in
  Proton's `~/.config/Proton/VPN/settings.json`

Kill Switch / NetShield / port forwarding only ever pass allow-listed
keys and values to `protonvpn config set`.

After sign-in the plugin rewrites `~/.local/share/keyrings/Default_keyring.keyring`
in place (fold Proton's literal newlines into GKeyFile `\\n`) and pins the
`default` alias file to that store. The same fold runs again if Proton later
writes raw newlines back; it no-ops when the INI is already clean. It does
not restart gnome-keyring or touch Hypr/Omarchy/systemd config.

Background `protonvpn status` is not polled while the panel is closed. That
CLI talks to Secret Service, and gnome-keyring 50 aborts on a racy
`Get(Label)`. The bar icon follows the tunnel via `nmcli` instead.

