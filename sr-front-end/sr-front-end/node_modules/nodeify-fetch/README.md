# nodeify-fetch
[![build status](https://img.shields.io/github/workflow/status/bergos/nodeify-fetch/Test)](https://github.com/bergos/nodeify-fetch/actions/workflows/test.yaml)
[![npm version](https://img.shields.io/npm/v/nodeify-fetch.svg)](https://www.npmjs.com/package/nodeify-fetch)

The `nodeify-fetch` package provides a Node.js [Readable](https://nodejs.org/api/stream.html#stream_class_stream_readable) stream interface for [fetch](https://fetch.spec.whatwg.org/).
In the browser, the built-in fetch is used.
In a Node.js environment, `node-fetch` it's used.

Since version 3.0, this packages is [ESM](https://nodejs.org/api/esm.html) only.
Check version 2.x if you are looking for a CommonJS package.

## Usage

The only difference to the fetch standard is the `.body` property.
`nodeify-fetch` patches the `.body` to a readable stream: 

```javascript
import { promisify } from 'util'
import fetch from 'nodeify-fetch'
import { finished } from 'readable-stream'

async function main () {
  const res = await fetch('http://worldtimeapi.org/api/timezone/etc/UTC')

  if (!res.ok) {
    console.log(`error ${res.statusText}(${res.status})`)
  }

  res.body.on('data', chunk => console.log(chunk.toString()))

  await promisify(finished)(res.body)
}

main()
```
