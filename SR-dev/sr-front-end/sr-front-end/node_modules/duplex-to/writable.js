const blackList = new Set(['_read', '_readableState', 'readable'])

function writable (duplex) {
  return new Proxy(duplex, {
    has (target, key) {
      if (blackList.has(key)) {
        return false
      }

      return Reflect.has(...arguments)
    },
    get (target, key) {
      if (blackList.has(key)) {
        return undefined
      }

      const result = Reflect.get(...arguments)

      if (result && typeof result.bind === 'function') {
        return result.bind(target)
      }

      return result
    },
    set (target, key, value) {
      if (blackList.has(key)) {
        return undefined
      }

      return Reflect.set(...arguments)
    }
  })
}

export default writable
