# AutoHeal node chaos agent: network tooling that must run in the node's
# network namespace (hostNetwork). Used to flush conntrack entries so that a
# freshly created NetworkPolicy also applies to already-established flows
# (most CNIs only evaluate policy for new connections).
FROM alpine:3.20
RUN apk add --no-cache conntrack-tools iproute2
CMD ["sh", "-c", "trap 'exit 0' TERM INT; while :; do sleep 3600 & wait $!; done"]
