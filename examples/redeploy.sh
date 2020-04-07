#!/bin/sh
#
# Reasons to first delete and then redeploy:
#   - Annotations aren't reverted when re-applying
#   - HPA reconciliation loop might delay next test

DIR=$(dirname $0)
NS=$1

if [ -z "${NS}" ]; then
    echo "Provide a namespace. Example: ${0} test-klutch"
    exit 1
fi

kubectl -n ${NS} delete cm klutch-status
kubectl -n ${NS} delete -f ${DIR}/scaling-app-demo.yaml
kubectl -n ${NS} apply -f ${DIR}/scaling-app-demo.yaml
