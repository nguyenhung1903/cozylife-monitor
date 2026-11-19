# Build
docker build -t cozylife-monitor .
# Run
docker run --name cozylife-monitor -p 8000:8000 --env-file .env cozylife-monitor