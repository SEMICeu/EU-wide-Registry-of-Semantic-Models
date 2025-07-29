class Patchable {
  constructor (obj, patch) {
    this.obj = obj

    for (const [key, value] of Object.entries(patch)) {
      this[key] = value
    }

    for (const key of Patchable.properties(obj)) {
      if (key in this) {
        continue
      }

      if (typeof this.obj[key] === 'function') {
        this[key] = (...args) => this.obj[key].call(obj, args)
      } else {
        Object.defineProperty(this, key, {
          get: () => {
            return this.obj[key]
          },
          set: value => {
            this.obj[key] = value
          },
          enumerable: true,
          configurable: true
        })
      }
    }
  }

  static properties (obj) {
    return Object.getOwnPropertyNames(Object.getPrototypeOf(obj))
  }
}

export default Patchable
