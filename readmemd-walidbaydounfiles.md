# walidBaydoun/files

## Introduction

The `walidBaydoun/files` repository provides a file management API designed to handle file uploads, retrieval, and management operations. The repository is structured to support robust handling of files, offering endpoints for uploading files, listing stored files, and retrieving specific file content. It leverages a modular architecture to keep logic separated for ease of maintenance and extensibility.

This project focuses on HTTP based interaction with a file storage backend. It exposes a clear set of routes that encapsulate all file related operations behind a simple interface.

Typical use cases include:

- Integrating file uploads into a web or mobile application.
- Storing and serving user generated documents or media.
- Managing a collection of files from an automated script or service.
- Building a small internal tool that requires basic file storage.

## Features

- Upload files via HTTP requests.
- List all files currently stored on the server.
- Retrieve the content of a specific file using its identifier.
- Organized modular structure for file operations and API routing.

These features allow both interactive clients and automated systems to manage files consistently. Each operation is exposed as a dedicated API endpoint, which simplifies integration and testing.

## Requirements

To run the code in this repository, ensure that you have the following installed:

- Node.js (version 14.x or above)
- npm (Node Package Manager)
- Express.js (web framework for Node.js)
- Multer (middleware for handling `multipart/form-data`, primarily used for file uploads)
- Standard Node.js modules such as `fs` and `path`

> [!IMPORTANT]
> Install all dependencies listed in the `package.json` file to ensure full functionality.

You also need:

- A terminal or command prompt to run Node.js commands.
- Network access to interact with the HTTP server from your client tools.
- Sufficient disk space on the machine to store uploaded files.

## Installation

Follow these steps to install and set up the repository:

```steps
1. Clone the repository | Clone the repository to your local machine using `git clone https://github.com/walidBaydoun/files.git`
2. Install dependencies | Navigate to the repository directory and run `npm install` to install required packages.
3. Start the server | Run `npm start` or `node index.js` (or the main entry file) to start the server.
```

> [!NOTE]
> The default storage directory for uploaded files will be created automatically if it does not exist.

After the server starts, it listens on the configured port and serves all defined file endpoints. You can then access the API using any HTTP client from the same machine or over the network, depending on your environment configuration.

## Usage

After installation and starting the server, you can interact with the API through HTTP requests. The API provides endpoints for uploading, listing, and retrieving files.

### Upload a File

Send a `POST` request with the file attached using form-data.

For example, using `curl`:

```bash
curl -X POST "http://localhost:3000/api/files/upload" \
  -F "file=@/path/to/local/file.ext"
```

### List Files

Send a `GET` request to retrieve metadata for all stored files.

Example using `curl`:

```bash
curl -X GET "http://localhost:3000/api/files/list"
```

### Retrieve a File

Send a `GET` request with a file identifier to fetch the file's content.

Example using `curl`:

```bash
curl -X GET "http://localhost:3000/api/files/<file-id>" -o output.ext
```

You can use tools like `curl`, Postman, or any HTTP client library to interact with the API endpoints. These examples demonstrate simple command line interactions and can be adapted to your preferred tooling.

## API Endpoints

### Upload File - POST `/api/files/upload`

```api
{
    "title": "Upload File",
    "description": "Uploads a file to the server storage.",
    "method": "POST",
    "baseUrl": "http://localhost:3000",
    "endpoint": "/api/files/upload",
    "headers": [
        {
            "key": "Content-Type",
            "value": "multipart/form-data",
            "required": true
        }
    ],
    "queryParams": [
        {
            "key": "folder",
            "value": "Optional logical folder or category name",
            "required": false
        }
    ],
    "pathParams": [],
    "bodyType": "form",
    "formData": [
        {
            "key": "file",
            "value": "The file to upload",
            "required": true
        }
    ],
    "requestBody": "",
    "responses": {
        "200": {
            "description": "File uploaded successfully",
            "body": "{\n  \"success\": true,\n  \"id\": \"unique-file-id\",\n  \"filename\": \"original-name.ext\",\n  \"size\": 12345\n}"
        },
        "400": {
            "description": "No file uploaded",
            "body": "{\n  \"success\": false,\n  \"error\": \"No file uploaded\"\n}"
        }
    }
}
```

This endpoint accepts a single file in a multipart form payload. The response includes an identifier that you can later use to retrieve or reference the uploaded file.

### List Files - GET `/api/files/list`

```api
{
    "title": "List Files",
    "description": "Retrieves metadata for all stored files.",
    "method": "GET",
    "baseUrl": "http://localhost:3000",
    "endpoint": "/api/files/list",
    "headers": [],
    "queryParams": [
        {
            "key": "limit",
            "value": "Maximum number of items to return",
            "required": false
        },
        {
            "key": "offset",
            "value": "Number of items to skip from the start",
            "required": false
        }
    ],
    "pathParams": [],
    "bodyType": "none",
    "requestBody": "",
    "responses": {
        "200": {
            "description": "List of files",
            "body": "[\n  {\n    \"id\": \"file-id\",\n    \"filename\": \"example.pdf\",\n    \"size\": 12345,\n    \"uploadedAt\": \"2023-01-01T12:34:56.789Z\"\n  }\n]"
        }
    }
}
```

The list endpoint returns an array of file records, each containing basic metadata. Optional query parameters enable simple pagination when many files exist.

### Retrieve File - GET `/api/files/:id`

```api
{
    "title": "Retrieve File",
    "description": "Fetches the content of a specific file using its identifier.",
    "method": "GET",
    "baseUrl": "http://localhost:3000",
    "endpoint": "/api/files/:id",
    "headers": [],
    "queryParams": [],
    "pathParams": [
        {
            "key": "id",
            "value": "Unique file identifier",
            "required": true
        }
    ],
    "bodyType": "none",
    "requestBody": "",
    "responses": {
        "200": {
            "description": "Returns file content",
            "body": "Binary file data"
        },
        "404": {
            "description": "File not found",
            "body": "{\n  \"error\": \"File not found\"\n}"
        }
    }
}
```

This endpoint streams or returns the raw file data for the requested file. Clients can save the response body directly to disk or process it in memory.

## Configuration

The repository allows configuration of the file storage path and server port via environment variables or a configuration file. The key configurable parameters include:

- **Storage Directory**: Directory path where files are stored. Set as an environment variable or directly in the code.
- **Server Port**: HTTP port for the API server. It can be customized through the `PORT` environment variable.

> [!TIP]
> Ensure the storage directory has write permissions for the server process.

Typical configuration options include:

- Defining a `.env` file to store environment specific values.
- Adjusting the port when deploying behind a reverse proxy or on shared hosts.
- Choosing a storage path located on a disk with sufficient capacity.

## Contributing

To contribute to `walidBaydoun/files`, please follow these steps:

- Fork the repository on GitHub.
- Clone your fork to your local machine.
- Create a new branch for your feature or bugfix.
- Implement your changes, following the existing code style.
- Write tests if applicable.
- Submit a pull request with a clear description of your changes.

> [!IMPORTANT]
> All contributions must comply with the repository's coding standards and should pass existing tests.

When opening a pull request, include information about which areas of the code you changed. If your work affects the API behavior, describe the new or modified endpoints and any changes to request or response formats.

---

For further details, consult the codebase and examine the main application and route files. The modular structure helps in understanding and extending file handling logic as needed.