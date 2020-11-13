GIT_TAG=0.1.test

echo "Setting all chart and image versions to: ${GIT_TAG}"


sed -i.bak "s/<<VERSION>>/$GIT_TAG/" charts/klutch/Chart.yaml
sed -i.bak "s/<<VERSION>>/$GIT_TAG/" charts/klutch/values.yaml
sed -i.bak "s/<<VERSION>>/$GIT_TAG/" charts/klutch-example/Chart.yaml
