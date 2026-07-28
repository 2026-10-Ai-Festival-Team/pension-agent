FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The application entry point will be added with the API implementation.
CMD ["python", "--version"]
