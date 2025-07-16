# stream-chunks
[![build status](https://img.shields.io/github/workflow/status/bergos/stream-chunks/Test)](https://github.com/bergos/stream-chunks/actions/workflows/test.yaml)
[![npm version](https://img.shields.io/npm/v/stream-chunks.svg)](https://www.npmjs.com/package/stream-chunks)

Get all chunks of a stream.

## Install

`npm install stream-chunks --save`

## Usage

There are multiple functions for collecting the chunks of a stream.
All of them are async functions, and expect the stream as the first argument.

### Raw as array

The `chunks` function collects all chunks and puts them in order in an array. 

```javascript
import chunks from 'stream-chunks/chunks.js'

const array = await chunks(stream)
```

### Combined into an Uint8Array

The `concat` function collects all chunks and combines them into a single Uint8Array object.

```javascript
import concat from 'stream-chunks/concat.js'

const all = await concat(stream)
```

### Combined into a string

The `decode` function collects all chunks, decodes them based on the given encoding, and combines them into a string.

```javascript
import decode from 'stream-chunks/decode.js'

const str = await decode(stream, 'utf8')
```
