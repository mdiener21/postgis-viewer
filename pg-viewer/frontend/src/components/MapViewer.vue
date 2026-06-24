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
  }
})

const mapContainer = ref(null)
let map = null

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
    updateMapData()
  })
})

watch(() => props.geojson, () => {
  updateMapData()
}, { deep: true })

function updateMapData() {
  if (!map || !map.isStyleLoaded()) return

  // Background map logic
  if (props.srid === 4326) {
    if (!map.getSource('osm')) {
      map.addSource('osm', {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '&copy; OpenStreetMap contributors'
      })
      map.addLayer({
        id: 'osm-layer',
        type: 'raster',
        source: 'osm'
      }, 'background') // Just above background
    }
  } else {
    if (map.getLayer('osm-layer')) map.removeLayer('osm-layer')
    if (map.getSource('osm')) map.removeSource('osm')
  }

  // Geometry data
  if (props.geojson && props.geojson.features && props.geojson.features.length > 0) {
    if (map.getSource('data')) {
      map.getSource('data').setData(props.geojson)
    } else {
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
    }

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

    // Popup on click
    map.on('click', 'data-fill', handleEvent)
    map.on('click', 'data-line', handleEvent)
    map.on('click', 'data-circle', handleEvent)
  }
}

function handleEvent(e) {
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
