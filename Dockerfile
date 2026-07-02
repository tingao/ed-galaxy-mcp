FROM python:3.13-alpine
WORKDIR /app
COPY frontier_auth.py .
EXPOSE 18080
CMD ["python", "frontier_auth.py"]
