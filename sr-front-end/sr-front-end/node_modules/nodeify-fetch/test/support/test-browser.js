#!/usr/bin/env node

import { $ } from 'zx'

import withServer from './server.js'

async function main () {
  await withServer(async server => {
    try {
      await server.listen(8080)

      await $`test-runner-browser --url=http://localhost:8080/`
    } catch (err) {
      console.error(err)
    }
  })
}

main()
