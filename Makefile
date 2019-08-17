IMAGE = valve_control
TEST_IMAGE = valve_control_test

.PHONY: docker test test-image

test: test-image
	docker run $(TEST_IMAGE)  tox

test-image: Dockerfile.test
	docker build -f Dockerfile.test -t $(TEST_IMAGE) .

image: Dockerfile
	docker build -f Dockerfile -t $(IMAGE) .
