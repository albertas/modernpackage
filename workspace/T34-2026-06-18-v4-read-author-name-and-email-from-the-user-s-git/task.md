# Task

Add the user's local git configuration (`user.name` and `user.email`) as a
source for author name and email defaults when scaffolding a new package. This
extends the existing metadata resolution so that, when an author name or email
is not supplied explicitly, the value can fall back to what is already
configured in the user's git config.
