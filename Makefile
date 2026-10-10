# Thin wrappers around the CLI (python -m novasurge ...). On Windows use .\nova.ps1 instead.
.PHONY: help demo up serve campaign dry-run train status report test down clean-cluster dashboard

help:
	@./nova.sh help

demo:          ## everything end-to-end
	./nova.sh demo
up:            ## create/update cluster + deploy (idempotent)
	./nova.sh up
serve:         ## dashboard + API on :8000 (autopilot on)
	./nova.sh serve
campaign:      ## 5-round chaos campaign (uses the running server if any)
	./nova.sh campaign
dry-run:       ## same campaign against the simulator
	./nova.sh campaign --dry-run
train:         ## retrain models on clean live baseline
	./nova.sh train
status:
	./nova.sh status
report:
	./nova.sh report
test:
	./nova.sh test
dashboard:
	./nova.sh dashboard-build
down:          ## pause the cluster (state kept)
	./nova.sh down
clean-cluster: ## delete the cluster entirely
	./nova.sh down --delete
