import { MongoClient } from 'mongodb'
import dotenv from 'dotenv'
import dns from 'dns'

dotenv.config()

// ── Force reliable DNS servers that support SRV lookups ──────────────
// Windows' default DNS resolver sometimes can't resolve mongodb+srv SRV
// records, causing "querySrv ECONNREFUSED". Google/Cloudflare DNS fixes this.
dns.setServers(['8.8.8.8', '8.8.4.4', '1.1.1.1'])

const uri = (process.env.MONGODB_URI || '').trim()
const client = uri
  ? new MongoClient(uri, {
      serverSelectionTimeoutMS: 30000,
      connectTimeoutMS        : 30000,
      socketTimeoutMS         : 30000,
    })
  : null

let dbInstance

function matchesFilter(doc, filter = {}) {
  return Object.entries(filter).every(([key, value]) => doc[key] === value)
}

function createCursor(sourceDocs) {
  let docs = [...sourceDocs]
  return {
    sort(sortSpec = {}) {
      const [[key, dir]] = Object.entries(sortSpec)
      docs.sort((a, b) => {
        const av = a[key]
        const bv = b[key]
        if (av === bv) return 0
        return av > bv ? dir : -dir
      })
      return this
    },
    limit(n) {
      docs = docs.slice(0, n)
      return this
    },
    project(fields = {}) {
      docs = docs.map((doc) => {
        const projected = {}
        for (const [field, include] of Object.entries(fields)) {
          if (include === 1 && Object.prototype.hasOwnProperty.call(doc, field)) {
            projected[field] = doc[field]
          }
        }
        return projected
      })
      return this
    },
    async toArray() {
      return docs
    },
  }
}

function createMemoryCollection(name) {
  const docs = []
  let idCounter = 1

  return {
    async countDocuments(filter = {}) {
      return docs.filter((doc) => matchesFilter(doc, filter)).length
    },
    async insertOne(doc) {
      if (name === 'users' && docs.some((d) => d.username === doc.username)) {
        throw new Error('E11000 duplicate key error collection: users index: username dup key')
      }
      const withId = {
        ...doc,
        _id: doc._id || String(idCounter++),
      }
      docs.push(withId)
      return { acknowledged: true, insertedId: withId._id }
    },
    async findOne(filter = {}) {
      return docs.find((doc) => matchesFilter(doc, filter)) || null
    },
    async updateOne(filter = {}, update = {}) {
      const idx = docs.findIndex((doc) => matchesFilter(doc, filter))
      if (idx === -1) return { acknowledged: true, matchedCount: 0, modifiedCount: 0 }
      const setOps = update.$set || {}
      docs[idx] = {
        ...docs[idx],
        ...setOps,
      }
      return { acknowledged: true, matchedCount: 1, modifiedCount: 1 }
    },
    find(filter = {}) {
      const matched = docs.filter((doc) => matchesFilter(doc, filter))
      return createCursor(matched)
    },
    aggregate() {
      // Minimal implementation for the patient summary route.
      const groupedMap = new Map()
      const sorted = [...docs].sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)))
      for (const p of sorted) {
        const key = `${p.patientId}::${p.eye}`
        if (!groupedMap.has(key)) {
          groupedMap.set(key, {
            patientId: p.patientId,
            eye: p.eye,
            lastAssessment: p.createdAt,
            recommendation: p.recommendedCorrection,
            monthsAfterDALK: p.monthsAfterDALK,
          })
        }
      }
      const result = [...groupedMap.values()].sort((a, b) =>
        String(b.lastAssessment).localeCompare(String(a.lastAssessment)),
      )
      return {
        async toArray() {
          return result
        },
      }
    },
  }
}

function createMemoryDb() {
  const collections = new Map()
  return {
    collection(name) {
      if (!collections.has(name)) {
        collections.set(name, createMemoryCollection(name))
      }
      return collections.get(name)
    },
  }
}

// Exported alias used by server.js as the Atlas-unreachable fallback
export { createMemoryDb as buildInMemoryDb }

export async function connectDb() {
  if (!dbInstance) {
    if (!client) {
      console.warn('MONGODB_URI is missing. Using in-memory database fallback.')
      dbInstance = createMemoryDb()
      return dbInstance
    }

    try {
      await client.connect()

      // Derive DB name from URI path or default to "postdalk"
      let dbName = 'postdalk'
      try {
        const parsed = new URL(uri)
        if (parsed.pathname && parsed.pathname !== '/') {
          dbName = parsed.pathname.replace('/', '')
        }
      } catch {
        // Fallback to default
      }

      dbInstance = client.db(dbName)
      console.log(`Connected to MongoDB database "${dbName}"`)
    } catch (error) {
      // Re-throw so connectDbWithRetry can retry the real MongoDB connection.
      // resetDbInstance() is called by the caller before each retry attempt.
      throw error
    }
  }

  return dbInstance
}

/**
 * Reset the cached DB instance so the next connectDb() call retries the
 * real MongoDB connection instead of reusing a stale in-memory fallback.
 */
export function resetDbInstance() {
  dbInstance = undefined
}

export function getDb() {
  if (!dbInstance) {
    throw new Error('Database not connected yet. Call connectDb() first.')
  }
  return dbInstance
}


