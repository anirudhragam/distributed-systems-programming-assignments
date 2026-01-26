
cp -r ../utils buyer-client/utils
cp -r ../utils seller-client/utils
cp -r ../utils buyer-server/utils
cp -r ../utils seller-server/utils

docker-compose up -d
echo "All services are up and running."

rm -rf buyer-client/utils
rm -rf seller-client/utils
rm -rf buyer-server/utils
rm -rf seller-server/utils