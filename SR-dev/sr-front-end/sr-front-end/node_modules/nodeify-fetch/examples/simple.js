import { promisify } from 'util'
import { finished } from 'readable-stream'
import fetch from '../index.js'

async function main () {
  const res = await fetch('http://worldtimeapi.org/api/timezone/etc/UTC')

  if (!res.ok) {
    console.log(`error ${res.statusText}(${res.status})`)
  }

  res.body.on('data', chunk => console.log(chunk.toString()))

  await promisify(finished)(res.body)
}

main()
