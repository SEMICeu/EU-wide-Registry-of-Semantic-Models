import assert from 'assert'
import { isStream, isReadableStream, isWritableStream } from 'is-stream'
import { describe, it } from 'mocha'
import { PassThrough } from 'readable-stream'
import decode from 'stream-chunks/decode.js'
import duplexToReadable from '../readable.js'

describe('readable', () => {
  it('should be a function', () => {
    assert.strictEqual(typeof duplexToReadable, 'function')
  })

  it('should return a stream', () => {
    const result = duplexToReadable(new PassThrough())

    assert(isStream(result))
  })

  it('should wrap only the readable interface', () => {
    const result = duplexToReadable(new PassThrough())

    assert(isReadableStream(result))
    assert(result.readable) // used by stream.finished
    assert(!isWritableStream(result))
    assert(!result.writable) // used by stream.finished
  })

  it('should keep object mode information', () => {
    const result = duplexToReadable(new PassThrough({ objectMode: true }))

    assert(result._readableState.objectMode)
  })

  it('should forward the content', async () => {
    const input = new PassThrough()
    const output = duplexToReadable(input)

    input.write('a')
    input.write('b')
    input.end('c')

    const result = await decode(output)

    assert.strictEqual(result, 'abc')
  })
})
