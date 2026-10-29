# Reviewable app integration template

For future application groups, merge release/ into MaintAI/.release and the
workflow template through a separate reviewed app PR. MLflow has already moved
to the canonical app module ml-service/mlflow and actual maintai-publish workflow;
do not overwrite that workflow with the broad template or enable skeleton groups.
The template delegates MLflow publication/dispatch to the canonical app publisher, so base
pins/smoke/signature policy are shared. It requires that module's release lockfile.
Read ../../docs/APP_INTEGRATION.md first. Publishing is gated off by default.
Implement real Dockerfiles/modules/probes, pin base/dependency versions and keep
runtime schema copies byte-identical to the GitOps-approved contract version.
No secrets belong in .release/contracts or public UI runtime configuration.
