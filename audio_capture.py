"""Windows 시스템 오디오(이어폰/스피커로 나가는 소리) 루프백 캡처.

Teams 소리가 이어폰으로 출력되는 것을 WASAPI 루프백으로 복사해서
16kHz mono 16bit PCM으로 변환해 넘겨준다.
주의: 출력 장치를 음소거하면 캡처할 소리도 사라진다. 볼륨은 0보다 크게 유지할 것.
"""
import asyncio
import queue
import sys

import numpy as np

import config

if sys.platform == "win32":
    import pyaudiowpatch as pyaudio
else:  # 개발/테스트용(리눅스 등)에서는 import만 가능하게 둔다
    pyaudio = None


def list_devices():
    """캡처 가능한 루프백 장치 목록을 출력한다."""
    if pyaudio is None:
        print("이 기능은 Windows에서만 동작합니다.")
        return
    p = pyaudio.PyAudio()
    try:
        print("=== 캡처 가능한 출력 장치(루프백) 목록 ===")
        for info in p.get_loopback_device_info_generator():
            print(f"- {info['name']}  (채널 {info['maxInputChannels']}, {int(info['defaultSampleRate'])}Hz)")
        print()
        print("Teams 소리가 나오는 장치 이름의 일부를 .env의 AUDIO_DEVICE_NAME에 적으세요.")
        print("비워두면 Windows 기본 출력 장치를 자동으로 사용합니다.")
    finally:
        p.terminate()


class AudioCapture:
    """출력 장치 루프백을 캡처해 16kHz mono PCM 청크를 내보낸다."""

    def __init__(self, device_name: str = "", target_rate: int = config.SEND_SAMPLE_RATE):
        if pyaudio is None:
            raise RuntimeError("오디오 캡처는 Windows에서만 지원됩니다 (PyAudioWPatch 필요).")
        self.device_name = device_name
        self.target_rate = target_rate
        self._q: queue.Queue[bytes] = queue.Queue(maxsize=200)
        self._p = None
        self._stream = None
        self._src_rate = 0
        self._channels = 1
        self._running = False
        self.level = 0.0        # 최근 입력 음량(0~1). 화면의 소리 미터용
        self.device_label = ""  # 캡처 중인 장치 이름. 화면 표시용

    def _find_device(self, p) -> dict:
        if self.device_name:
            for info in p.get_loopback_device_info_generator():
                if self.device_name.lower() in info["name"].lower():
                    return info
            raise RuntimeError(
                f"'{self.device_name}' 이름을 포함한 루프백 장치를 찾지 못했습니다. "
                "`python main.py --list-devices` 로 이름을 확인하세요."
            )
        # 이름 미지정 → 기본 출력 장치의 루프백을 사용
        return p.get_default_wasapi_loopback()

    def start(self):
        self._p = pyaudio.PyAudio()
        info = self._find_device(self._p)
        self._src_rate = int(info["defaultSampleRate"])
        self._channels = max(1, int(info["maxInputChannels"]))
        frames = max(1, self._src_rate // 10)  # 100ms 단위
        self._running = True
        self._stream = self._p.open(
            format=pyaudio.paInt16,
            channels=self._channels,
            rate=self._src_rate,
            input=True,
            input_device_index=info["index"],
            frames_per_buffer=frames,
            stream_callback=self._callback,
        )
        self.device_label = info["name"]
        print(f"[오디오] 캡처 시작: {info['name']} ({self._src_rate}Hz, {self._channels}ch)")

    def _callback(self, in_data, frame_count, time_info, status):
        pcm = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
        if self._channels > 1:
            pcm = pcm.reshape(-1, self._channels).mean(axis=1)
        self.level = min(1.0, float(np.sqrt(np.mean(pcm ** 2))) / 8000.0)
        # 선형 보간으로 16kHz 리샘플
        if self._src_rate != self.target_rate:
            n_out = int(len(pcm) * self.target_rate / self._src_rate)
            if n_out == 0:
                return (None, pyaudio.paContinue)
            x_out = np.linspace(0, len(pcm) - 1, n_out)
            pcm = np.interp(x_out, np.arange(len(pcm)), pcm)
        chunk = np.clip(pcm, -32768, 32767).astype(np.int16).tobytes()
        try:
            self._q.put_nowait(chunk)
        except queue.Full:
            pass  # 소비가 밀리면 해당 청크만 버린다 (실시간성 우선)
        return (None, pyaudio.paContinue)

    def _get_chunk(self):
        # 무한 대기하면 Ctrl+C 종료 시 대기 스레드가 안 풀려 프로세스가 멈추므로 짧게 끊어서 대기
        try:
            return self._q.get(timeout=0.5)
        except queue.Empty:
            return None

    async def chunks(self):
        """비동기 제너레이터: 16kHz mono PCM 청크를 순서대로 내보낸다."""
        loop = asyncio.get_running_loop()
        while self._running:
            data = await loop.run_in_executor(None, self._get_chunk)
            if data is not None:
                yield data

    def stop(self):
        self._running = False
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
        if self._p is not None:
            self._p.terminate()
