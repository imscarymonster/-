// 语音 TTS 播报工具
// 用于到站提醒与调度指令语音播报

let synth = null

function getSynth() {
  if (!synth && window.speechSynthesis) {
    synth = window.speechSynthesis
  }
  return synth
}

/** 播报到站倒计时 */
export function speakArrival(stationName, seconds) {
  const s = getSynth()
  if (!s) return

  const minutes = Math.floor(seconds / 60)
  const text = minutes > 0
    ? `车辆预计${minutes}分钟后到达${stationName}`
    : `车辆即将到达${stationName}`

  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = 'zh-CN'
  utter.rate = 0.9
  s.speak(utter)
}

/** 播报调度指令 */
export function speakDispatch(instruction) {
  const s = getSynth()
  if (!s) return

  const utter = new SpeechSynthesisUtterance(instruction)
  utter.lang = 'zh-CN'
  utter.rate = 1.0
  s.speak(utter)
}
