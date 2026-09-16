/** Draws the current video frame to a canvas and encodes it as JPEG. */
export function grabFrame(video: HTMLVideoElement, quality = 0.92): Promise<Blob> {
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  const ctx = canvas.getContext('2d')
  if (!ctx || canvas.width === 0) {
    return Promise.reject(new Error('The camera has not produced a frame yet.'))
  }
  ctx.drawImage(video, 0, 0)
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Could not encode the frame.'))), 'image/jpeg', quality)
  })
}
