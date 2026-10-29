# Replace the reviewed base-image digest before publishing; no floating release tag.
ARG PYTHON_BASE_IMAGE
FROM ${PYTHON_BASE_IMAGE}
WORKDIR /opt/maintai-platform
COPY runtime/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY automation/ ./automation/
COPY contracts/ ./contracts/
COPY config/ ./config/
COPY runtime/platform_runtime/ ./platform_runtime/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
ENTRYPOINT ["python", "-m", "platform_runtime.lifecycle"]
