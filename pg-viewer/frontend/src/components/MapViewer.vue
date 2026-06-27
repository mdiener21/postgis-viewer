<script setup>
import { ref, onMounted, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

const props = defineProps({
  geojson: {
    type: Object,
    default: null
  },
  srid: {
    type: Number,
    default: 0
  },
  queryId: {
    type: String,
    default: null
  },
  bbox: {
    type: Array,
    default: null
  }
})

const mapContainer = ref(null)
let map = null
const mapReady = ref(false)

onMounted(() => {
  map = new maplibregl.Map({
    container: mapContainer.value,
    style: {
      version: 8,
      sources: {},
      layers: [
        {
          id: 'background',
          type: 'background',
          paint: { 'background-color': '#f8f9fa' }
        }
      ]
    },
    center: [0, 0],
    zoom: 1
  })

  map.on('load', () => {
    mapReady.value = true
    updateMapData()
  })
})

// Redraw whenever the data arrives OR the map finishes loading, whichever is
// last. `immediate` covers the case where MapViewer mounts with props already
// set, and watching mapReady covers data that arrives before the style loads.
watch(
  [() => props.geojson, () => props.queryId, mapReady],
  () => {
    updateMapData()
  },
  { deep: true, immediate: true }
)

function updateMapData() {
  if (!map || !mapReady.value) return

  // Background map logic
  const shouldShowOSM = props.srid === 4326 || props.queryId;

  if (shouldShowOSM) {
    if (!map.getSource('osm')) {
      map.addSource('osm', {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '&copy; OpenStreetMap contributors'
      })
      // Add it without beforeId so it's on top of the background layer.
      // Data layers added later will be on top of this.
      map.addLayer({
        id: 'osm-layer',
        type: 'raster',
        source: 'osm'
      })
    }
    // Ensure it's visible if it was hidden/removed
    if (map.getLayer('osm-layer')) {
        map.setLayoutProperty('osm-layer', 'visibility', 'visible')
    }
  } else {
    if (map.getLayer('osm-layer')) {
        map.setLayoutProperty('osm-layer', 'visibility', 'none')
    }
  }

  // Clear existing data layers/sources if they exist and we're switching modes
  const removeData = () => {
    ['data-fill', 'data-line', 'data-circle'].forEach(id => {
      if (map.getLayer(id)) map.removeLayer(id)
    })
    if (map.getSource('data')) map.removeSource('data')
  }

  // Vector Tile Data
  if (props.queryId) {
    removeData()
    map.addSource('data', {
      type: 'vector',
      tiles: [`${window.location.origin}/api/tiles/${props.queryId}/{z}/{x}/{y}`],
      minzoom: 0,
      maxzoom: 22
    })

    map.addLayer({
      id: 'data-fill',
      type: 'fill',
      source: 'data',
      'source-layer': 'default',
      filter: ['==', '$type', 'Polygon'],
      paint: {
        'fill-color': '#3b82f6',
        'fill-opacity': 0.5,
        'fill-outline-color': '#1d4ed8'
      }
    })

    map.addLayer({
      id: 'data-line',
      type: 'line',
      source: 'data',
      'source-layer': 'default',
      filter: ['==', '$type', 'LineString'],
      paint: {
        'line-color': '#3b82f6',
        'line-width': 2
      }
    })

    map.addLayer({
      id: 'data-circle',
      type: 'circle',
      source: 'data',
      'source-layer': 'default',
      filter: ['==', '$type', 'Point'],
      paint: {
        'circle-radius': 6,
        'circle-color': '#3b82f6',
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffffff'
      }
    })

    if (props.bbox) {
        map.fitBounds(props.bbox, { padding: 50, maxZoom: 15 })
    }

    // Use a single click listener on the map and check for features
    // instead of adding multiple listeners that accumulate
    map.off('click', handleLayerClick)
    map.on('click', handleLayerClick)
  }
  // GeoJSON data (fallback or legacy)
  else if (props.geojson && props.geojson.features && props.geojson.features.length > 0) {
    removeData()
    map.addSource('data', {
      type: 'geojson',
      data: props.geojson
    })

    map.addLayer({
      id: 'data-fill',
      type: 'fill',
      source: 'data',
      filter: ['==', '$type', 'Polygon'],
      paint: {
        'fill-color': '#3b82f6',
        'fill-opacity': 0.5,
        'fill-outline-color': '#1d4ed8'
      }
    })

    map.addLayer({
      id: 'data-line',
      type: 'line',
      source: 'data',
      filter: ['==', '$type', 'LineString'],
      paint: {
        'line-color': '#3b82f6',
        'line-width': 2
      }
    })

    map.addLayer({
      id: 'data-circle',
      type: 'circle',
      source: 'data',
      filter: ['==', '$type', 'Point'],
      paint: {
        'circle-radius': 6,
        'circle-color': '#3b82f6',
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffffff'
      }
    })

    // Fit bounds
    const bounds = new maplibregl.LngLatBounds()
    props.geojson.features.forEach(feature => {
        if (feature.geometry) {
            const coords = feature.geometry.coordinates
            if (feature.geometry.type === 'Point') {
                bounds.extend(coords)
            } else if (feature.geometry.type === 'LineString' || feature.geometry.type === 'MultiPoint') {
                coords.forEach(c => bounds.extend(c))
            } else if (feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiLineString') {
                coords.forEach(ring => ring.forEach(c => bounds.extend(c)))
            } else if (feature.geometry.type === 'MultiPolygon') {
                coords.forEach(poly => poly.forEach(ring => ring.forEach(c => bounds.extend(c))))
            }
        }
    })
    
    if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 50, maxZoom: 15 })
    }

    map.off('click', handleLayerClick)
    map.on('click', handleLayerClick)
  }
}

function handleLayerClick(e) {
  const features = map.queryRenderedFeatures(e.point, {
    layers: ['data-fill', 'data-line', 'data-circle']
  })

  if (!features.length) return

  const properties = features[0].properties
  let content = '<div class="p-2 font-sans text-xs max-h-40 overflow-y-auto"><table class="w-full">'
  for (const [key, value] of Object.entries(properties)) {
    content += `<tr><td class="font-bold pr-2">${key}:</td><td>${value}</td></tr>`
  }
  content += '</table></div>'

  new maplibregl.Popup()
    .setLngLat(e.lngLat)
    .setHTML(content)
    .addTo(map)
}

function handleEvent(e) {
  // Legacy handler for GeoJSON mode
  const properties = e.features[0].properties
  let content = '<div class="p-2 font-sans text-xs max-h-40 overflow-y-auto"><table class="w-full">'
  for (const [key, value] of Object.entries(properties)) {
    content += `<tr><td class="font-bold pr-2">${key}:</td><td>${value}</td></tr>`
  }
  content += '</table></div>'

  new maplibregl.Popup()
    .setLngLat(e.lngLat)
    .setHTML(content)
    .addTo(map)
}
</script>

<template>
  <div ref="mapContainer" class="w-full h-full rounded-lg border shadow-inner bg-slate-50"></div>
</template>

<style>
.maplibregl-popup-content {
  padding: 0;
  border-radius: 8px;
}
</style>
