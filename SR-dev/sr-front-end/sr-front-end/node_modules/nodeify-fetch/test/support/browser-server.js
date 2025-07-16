async function withServer (callback) {
  const server = {
    listen: () => 'http://localhost:8080/'
  }

  await callback(server)
}

export default withServer
