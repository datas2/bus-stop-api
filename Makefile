# virtual environment commands
venv-create:
	python3 -m venv venv

venv-up:
	source venv/bin/activate

venv-down:
	deactivate

# python commands
install-pip:
	pip install --upgrade pip
	pip install -r requirements.txt --upgrade

freeze-pip:
	pip freeze > requirements.txt

# tests commands
run-tests:
	pytest tests --disable-warnings

# fastapi commands
run-fastapi:
	uvicorn main:app --reload

# docker commands
build-docker:
	docker build -t bus-stop-api .

run-docker:
	docker run -d -p 8000:8000 --name bus-stop-api bus-stop-api

stop-docker:
	docker stop bus-stop-api
	docker rm bus-stop-api

# cloudrun commands
login-artifact-registry:
	gcloud auth configure-docker us-central1-docker.pkg.dev

build-image:
	docker buildx build --platform linux/amd64 -t us-central1-docker.pkg.dev/project-c81c4edd-4dfa-4b1c-bf8/bus-stop-api/api .


create-repository:
	gcloud artifacts repositories create bus-stop-api \
		--repository-format=docker \
		--location=us-central1 \
		--description="Docker repository for Auckland Bus Stop API"

push-image:
	docker push us-central1-docker.pkg.dev/project-c81c4edd-4dfa-4b1c-bf8/bus-stop-api/api

deploy-cloudrun:
	gcloud run deploy bus-stop-api \
		--image us-central1-docker.pkg.dev/project-c81c4edd-4dfa-4b1c-bf8/bus-stop-api/api \
		--region us-central1 \
		--set-env-vars API_KEY=auckland-bus-stop_KThuXqIVRbdt8b4gK9leJMJJvRXtlwAZ \
		--memory 256Mi \
		--cpu 1 \
		--max-instances 1 \
		--timeout 60 \
		--allow-unauthenticated