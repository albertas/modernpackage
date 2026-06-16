# Task

Make the test suite deterministic and fast. Configure the test runner to
execute tests in parallel with pytest-xdist using all-but-one available CPU
cores, and ensure unit tests are mocked rather than calling external API
endpoints or network services (latency cost), reserving real external calls for
explicit end-to-end tests only.
