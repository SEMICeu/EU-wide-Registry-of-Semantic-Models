const isStream = require('isstream')
const { PassThrough } = require('readable-stream')
const duplexToReadable = require('../readable')

// dummy function which
//   - doesn't accept streams with writable interface
//   - just writes the incoming data to stdout
function noWritablesAccepted (stream) {
  if (isStream.isWritable(stream)) {
    throw new Error('no writable streams supported')
  }

  stream.on('data', chunk => process.stdout.write(chunk))
}

const stream = new PassThrough()
const readable = duplexToReadable(stream)

// the next line would throw an error if it would be called with stream
noWritablesAccepted(readable)

stream.write('Hello ')
stream.end('World!\n')
