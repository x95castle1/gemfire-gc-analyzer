# Variables
IMAGE_NAME = gemfire-analyzer
PORT = 8501

.PHONY: help
help:
	@echo "Available commands:"
	@echo "  make build  - Build the Docker image"
	@echo "  make run    - Run the Docker container on port $(PORT)"
	@echo "  make stop   - Stop the running container"
	@echo "  make clean  - Remove the Docker image"

.PHONY: build
build:
	docker build -t $(IMAGE_NAME) .

.PHONY: run
run:
	docker run -p $(PORT):$(PORT) --rm --name $(IMAGE_NAME)-app $(IMAGE_NAME)

.PHONY: stop
stop:
	docker stop $(IMAGE_NAME)-app

.PHONY: clean
clean:
	docker rmi $(IMAGE_NAME)