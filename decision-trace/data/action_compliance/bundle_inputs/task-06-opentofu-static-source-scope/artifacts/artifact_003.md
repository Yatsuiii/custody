# Pinned code boundary

Pinned source: `opentofu/opentofu@3fdc8090501234c55093078255969ecbc46f2fe2`.

At the pin, `internal/configs/module_call.go` eagerly decodes the module source
attribute into a string and address, discarding the expression as a first-class
field. `internal/configs/module_merge.go` propagates source address fields when
an override replaces the source. Module block labels are fixed parser identity
strings.

The requested patch introduces only the expression retention needed by the
accepted source-attribute work.
