echo "Setting all chart and image versions to: ${GIT_TAG}"

sed -i.bak "s/0\.0\.0/$GIT_TAG/" charts/klutch/Chart.yaml
sed -i.bak "s/0\.0\.0/$GIT_TAG/" charts/klutch/values.yaml
sed -i.bak "s/0\.0\.0/$GIT_TAG/" charts/klutch-example/Chart.yaml
