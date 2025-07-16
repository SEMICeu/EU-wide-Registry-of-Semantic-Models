# duplex-to
[![build status](https://img.shields.io/github/workflow/status/bergos/duplex-to/Test)](https://github.com/bergos/duplex-to/actions/workflows/test.yaml)
[![npm version](https://img.shields.io/npm/v/duplex-to.svg)](https://www.npmjs.com/package/duplex-to)

`duplex-to` wraps a duplex stream with a `Proxy` and hides the readable or the writable interface.
Hidding part of the interface can be useful in cases where errors are thrown or the code behaves different based on the interface type. 
This package allows to show only one part of a duplex stream for those cases.

## Usage

### readable

The `readable` function wraps a duplex stream to show only the readable interface.
It can be loaded either by path or from the main module by property:

```js
import readable from 'duplex-to/readable.js'
import { readable } from 'duplex-to'
```

The function is a factory which returns the wrapped stream.
The stream which should be wrapped must be given as argument:

```js
const readableStream = readable(duplexStream)
````

### writable

The `writable` function wraps a duplex stream to show only the writable interface.
It can be loaded either by path or from the main module by property:

```js
import writable from 'duplex-to/writable.js'
import { writable } from 'duplex-to'
```

The function is a factory which returns the wrapped stream.
The stream which should be wrapped must be given as argument:

```js
const writableStream = writable(duplexStream)
````

## Example

The following examples creates a `PassThrough` duplex stream, which is used to write a text string and allows to access it via the readable stream interface.
The function `noWritablesAccepted` accepts only readable streams and writes the data from the stream to `stdout`.
Passing the `PassThrough` object to the function would throw an error, but with the wrapper only the readable part is visible to the function.

```js
import duplexToReadable from 'duplex-to/readable.js'
import { isWritableStream } from 'is-stream'
import { PassThrough } from 'readable-stream'

// dummy function which
//   - doesn't accept streams with writable interface
//   - just writes the incoming data to stdout 
function noWritablesAccepted (stream) {
  if (isWritableStream(stream)) {
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
```
