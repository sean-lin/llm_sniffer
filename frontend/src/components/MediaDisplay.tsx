import type { MediaFile } from '../types';
import { mediaUrl } from '../api';

interface Props {
  media: MediaFile[];
}

export default function MediaDisplay({ media }: Props) {
  if (media.length === 0) return null;

  return (
    <div className="media-display">
      {media.map(m => (
        <div key={m.id} className="media-item">
          {m.media_type === 'image' ? (
            <img src={mediaUrl(m.file_path)} alt="media" className="media-image" />
          ) : (
            <audio controls src={mediaUrl(m.file_path)} className="media-audio" />
          )}
          <span className="media-label">{m.mime_type}</span>
        </div>
      ))}
    </div>
  );
}
