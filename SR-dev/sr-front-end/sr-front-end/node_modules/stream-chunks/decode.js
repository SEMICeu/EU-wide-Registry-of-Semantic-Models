import { StringDecoder } from 'string_decoder'

async function decode (stream, encoding) {
  const decoder = new StringDecoder(encoding)
  let str = ''

  for await (const chunk of stream) {
    str += decoder.write(chunk)
  }

  str += decoder.end()

  return str
}

export default decode
