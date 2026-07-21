# Task

Add a Justfile recipe that increments the patch component of the package
version programmatically, and have the `publish` recipe run this bump before
building and publishing. This ensures every publish ships a new version without
requiring a manual version edit.
