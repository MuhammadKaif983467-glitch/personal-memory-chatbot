import { ImportPanel } from '../components/ImportPanel'

type Props = {
  onImported: (personId?: number | null) => void
}

export function ImportPage(props: Props) {
  return <div className="content-scroll"><ImportPanel {...props} /></div>
}
