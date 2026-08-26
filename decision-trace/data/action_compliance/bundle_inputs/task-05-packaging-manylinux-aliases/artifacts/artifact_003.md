# Pinned code boundary

Pinned source: `pypa/packaging@19fbc45b24ca0d577c9b256bb404b0dbaf4903da`.

At this commit, `packaging/tags.py` supports the three discrete legacy
manylinux policies but does not yet generate PEP 600 perennial tags. The task
patch replaces that generation path with a glibc-version sequence. Both sanity
patches therefore implement real tag-generation behavior against an immutable
public snapshot.
