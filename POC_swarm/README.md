# WebRTC P2P Number Swarm (browser demo)

A proof of concept for serverless peer discovery: peers find each other in a
public IRC channel, exchange WebRTC signalling over IRC private messages, then
talk directly browser-to-browser. Each peer holds a number, and the swarm
collectively computes the maximum.

The point of the demo is the **rendezvous pattern**, not the number: a public,
free, well-known channel used purely for introductions, after which traffic
leaves the channel entirely.

## Status: does not run in a browser yet

Be clear about this before spending time on it. The original version of this
demo had never been executed — `node --check app.js` failed outright.

**Fixed in this revision (all verified by `test_signal_chunking.js`):**

1. **Syntax error, whole file.** The nick sanitiser used the character class
   `[^a-zA-Z0-9_-\[...]`, in which `_-\[` parses as a range from `_` (0x5F) to
   `[` (0x5B) — "Range out of order in character class". The script never
   parsed, so none of it had ever run.
2. **Off-by-two in the signal parser.** `"WEBRTC_SIGNAL:".length` is 14, but the
   receive path sliced at `substring(16)`, so every `JSON.parse` threw.
3. **No chunking.** An IRC protocol line is capped at 512 bytes including the
   `PRIVMSG <target> :` prefix and CRLF. WebRTC SDP offers are routinely 1–4 KB.
   Every offer would have been truncated. Signals are now split, tagged
   `msgId:index:total`, and reassembled — tolerant of out-of-order and
   duplicate chunks, with a 60s TTL on incomplete transfers.
4. **`irc-framework` was never loaded.** `index.html` had the script tag
   commented out, and placed *after* `app.js`, which uses it at startup.

**Still blocking, and not fixable in-page:**

5. **A browser cannot open a raw TCP socket.** `irc.libera.chat:6697` is plain
   TLS-over-TCP, which is unreachable from page JavaScript regardless of which
   library is loaded. Running this in a browser requires a WebSocket-to-IRC
   gateway (e.g. `kiwiirc/webircgateway`) that you host.

That last item is worth sitting with, because it undercuts the demo's own
premise: adding a gateway reintroduces exactly the server the design set out to
remove. The rendezvous idea survives; the *browser* delivery of it does not.

## Running it

**Recommended — the version that works today:**

```bash
python3.11 ../swarm/irc_rendezvous.py --channel '#poc-swarm-discovery'
```

Same rendezvous pattern, no gateway, no bundler, standard library only.

**Browser version**, if you want to finish it:

1. Build the bundle and uncomment the script tag (see `index.html`).
2. Stand up a WebSocket→IRC gateway and point `ircOptions` at it.
3. Open `index.html` in two or more tabs.

Peers appear in the peer list after HELLO discovery, and "Swarm Maximum"
converges across all instances.

## Tests

```bash
node test_signal_chunking.js
```

Loads `app.js` into a `vm` context with a stubbed DOM and exercises the
signalling transport: single-chunk round trip, 4 KB SDP across many chunks,
line-length ceiling, out-of-order delivery, duplicate chunks, incomplete
signals, malformed headers, and send-while-disconnected.

## Known limitations beyond the above

- **No authentication.** Any channel occupant can send a `HELLO` or a
  `WEBRTC_SIGNAL`. Peer identity is a self-asserted random string. Do not put
  anything trust-bearing on this channel — see `../docs/04-open-questions.md`.
- **Libera.Chat is a real network with real operators.** It has connection
  limits and policies on bots. Use a test channel, keep announcement rates low,
  and register if you intend sustained use.
- **NAT traversal** uses a public STUN server only. Symmetric NATs will need
  TURN, which is not free.
- Chunking splits on UTF-16 code units, not bytes. Fine for SDP and ICE
  candidates, which are ASCII; revisit before sending arbitrary Unicode.
