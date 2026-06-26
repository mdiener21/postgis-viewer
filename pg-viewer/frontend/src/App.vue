<script setup>
import { ref, reactive } from 'vue'
import { Search, Map as MapIcon, Table as TableIcon, Layers, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import MapViewer from '@/components/MapViewer.vue'

const sql = ref("SELECT * FROM sample_points")
const results = ref(null)
const mapData = ref(null)
const loading = ref(false)
const error = ref(null)
const viewMode = ref('table') // 'table' or 'map'

async function runQuery(page = 1) {
  loading.value = true
  error.value = null
  try {
    const response = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql: sql.value, page, page_size: 10 })
    })
    const data = await response.json()
    if (response.ok) {
      results.value = data
    } else {
      error.value = data.detail
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function showOnMap() {
  loading.value = true
  try {
    const response = await fetch('/api/map-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql: sql.value })
    })
    const data = await response.json()
    if (response.ok) {
      mapData.value = data
      viewMode.value = 'map'
    } else {
      error.value = data.detail
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 flex flex-col p-4 md:p-8 space-y-6">
    <header class="flex flex-col space-y-2">
      <h1 class="text-3xl font-bold tracking-tight text-slate-900">PostGIS MapLibre Viewer</h1>
      <p class="text-slate-500">Fast visualization for your spatial queries.</p>
    </header>

    <Card class="border-slate-200 shadow-sm">
      <CardHeader class="pb-3">
        <CardTitle class="text-lg font-medium">SQL Query</CardTitle>
      </CardHeader>
      <CardContent class="space-y-4">
        <textarea
          v-model="sql"
          class="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 font-mono"
          placeholder="SELECT * FROM my_table..."
        ></textarea>
        <div class="flex items-center space-x-2">
          <Button @click="() => runQuery(1)" :disabled="loading" class="bg-blue-600 hover:bg-blue-700">
            <Search class="w-4 h-4 mr-2" />
            Run Query
          </Button>
          <Button
            v-if="results && Object.keys(results.geometry_columns).length > 0"
            variant="outline"
            @click="showOnMap"
            :disabled="loading"
          >
            <MapIcon class="w-4 h-4 mr-2 text-blue-600" />
            View on Map
          </Button>
        </div>
      </CardContent>
    </Card>

    <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
      {{ error }}
    </div>

    <div v-if="results" class="flex-1 flex flex-col min-h-0 space-y-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <Button
            variant="ghost"
            size="sm"
            :class="{ 'bg-white shadow-sm border': viewMode === 'table' }"
            @click="viewMode = 'table'"
          >
            <TableIcon class="w-4 h-4 mr-2" />
            Table
          </Button>
          <Button
            v-if="mapData"
            variant="ghost"
            size="sm"
            :class="{ 'bg-white shadow-sm border': viewMode === 'map' }"
            @click="viewMode = 'map'"
          >
            <MapIcon class="w-4 h-4 mr-2" />
            Map
          </Button>
        </div>
        
        <div v-if="viewMode === 'table'" class="flex items-center space-x-2 text-sm text-slate-500">
           <span>Page {{ results.page }}</span>
           <div class="flex space-x-1">
             <Button variant="outline" size="icon" class="h-8 w-8" :disabled="results.page === 1" @click="runQuery(results.page - 1)">
               <ChevronLeft class="h-4 w-4" />
             </Button>
             <Button variant="outline" size="icon" class="h-8 w-8" @click="runQuery(results.page + 1)">
               <ChevronRight class="h-4 w-4" />
             </Button>
           </div>
        </div>
      </div>

      <div class="flex-1 min-h-[400px] bg-white rounded-lg border border-slate-200 overflow-hidden relative">
        <div v-if="viewMode === 'table'" class="h-full overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead v-for="col in results.columns" :key="col" class="whitespace-nowrap">
                  {{ col }}
                  <Badge v-if="results.geometry_columns[col] !== undefined" variant="secondary" class="ml-1 text-[10px] px-1 py-0">
                    SRID:{{ results.geometry_columns[col] }}
                  </Badge>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="(row, i) in results.rows" :key="i">
                <TableCell v-for="col in results.columns" :key="col" class="max-w-[200px] truncate text-xs">
                  {{ row[col] }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
        
        <div v-if="viewMode === 'map'" class="absolute inset-0">
          <MapViewer
            :geojson="mapData"
            :srid="mapData?.srid"
            :query-id="mapData?.query_id"
            :bbox="mapData?.bbox"
          />
          <div class="absolute top-4 right-4 z-10">
             <Badge variant="outline" class="bg-white shadow-sm backdrop-blur-sm">
                SRID: {{ mapData?.srid }}
             </Badge>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* Custom transitions can go here */
</style>
