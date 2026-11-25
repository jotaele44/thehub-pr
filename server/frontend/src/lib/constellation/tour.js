// Tour state for the Federation Constellation: which stage is showing, whether
// the flythrough is playing, which lens is drawn and which node is selected.
// A plain reducer so the page drives it with useReducer and tests drive it directly.

export function initialTour({ stageCount, stageIndex = 0, lens = 'code', selectedId = null, playing = true }) {
  return {
    stageCount,
    stageIndex: Math.min(Math.max(0, stageIndex), Math.max(0, stageCount - 1)),
    lens,
    selectedId,
    playing: playing && stageCount > 1,
  };
}

const wrap = (index, count) => ((index % count) + count) % count;

export function tourReducer(state, action) {
  const count = Math.max(1, state.stageCount);
  switch (action.type) {
    case 'PLAY':
      // Playing again from the closing overview restarts the tour.
      return { ...state, playing: true, stageIndex: state.stageIndex === count - 1 ? 0 : state.stageIndex };
    case 'PAUSE':
    case 'USER_INTERACT':
      return state.playing ? { ...state, playing: false } : state;
    case 'TOGGLE_PLAY':
      return tourReducer(state, { type: state.playing ? 'PAUSE' : 'PLAY' });
    case 'ADVANCE':
      // The timer's tick: loop back to the start after the overview.
      return state.playing ? { ...state, stageIndex: wrap(state.stageIndex + 1, count), selectedId: null } : state;
    case 'NEXT':
      return { ...state, stageIndex: wrap(state.stageIndex + 1, count), selectedId: null };
    case 'PREV':
      return { ...state, stageIndex: wrap(state.stageIndex - 1, count), selectedId: null };
    case 'GOTO': {
      const index = Math.min(Math.max(0, action.index), count - 1);
      return index === state.stageIndex ? state : { ...state, stageIndex: index, selectedId: null };
    }
    case 'SET_LENS':
      // The caller passes the counterpart of the selection in the new lens.
      return state.lens === action.lens ? state : { ...state, lens: action.lens, selectedId: action.selectedId ?? null };
    case 'SELECT':
      return { ...state, selectedId: action.id, playing: false,
        stageIndex: action.stageIndex ?? state.stageIndex };
    case 'CLEAR_SELECTION':
      return state.selectedId ? { ...state, selectedId: null } : state;
    default:
      return state;
  }
}
