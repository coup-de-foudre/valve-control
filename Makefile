IMAGE = valve_control
TEST_IMAGE = valve_control_test

.PHONY: docker test test-image

test: test-image
	docker run $(TEST_IMAGE)  tox

test-image: Dockerfile.test
	docker build -f Dockerfile.test -t $(TEST_IMAGE) .

image: Dockerfile
	docker build -f Dockerfile -t $(IMAGE) .

.PHONY: daemon
daemon:
	sudo cp ./deploy/valve-control.service /lib/systemd/system/valve_control.service
	sync
	sudo systemctl daemon-reload valve_control
	sudo systemctl enable
	sudo systemctl start valve_control

.PHONY: logs
logs:
	sudo journalctl --follow -n 50 _SYSTEMD_UNIT=valve_control.service
