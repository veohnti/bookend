import booksy from '../assets/booksy.png'

// Booksy: the orange cat with glasses and a book, the face of Bookend's AI reading companion.
export default function Booksy({ size = 48, className = '' }: { size?: number; className?: string }) {
  return <img className={`booksy ${className}`} src={booksy} alt="Booksy, your AI reading companion" style={{ height: size }} />
}
