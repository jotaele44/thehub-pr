// satellite.js 7 can propagate many satellites at once through a WebAssembly runtime it loads with
// import('#wasm-single-thread') and import('#wasm-multi-thread'). The Sky workspace uses only the plain JavaScript
// SGP4 (json2satrec / propagate), so vite.config.js points those two specifiers here and the 309 KB Emscripten
// module is not built into the app. If something ever calls the bulk API, this says why it cannot run.
export default function wasmPropagationIsNotBuiltIn() {
  throw new Error('satellite.js WebAssembly propagation is not built into this app; use propagate() from src/sky/satellites.js.');
}
