import { SettingsPanel } from '../components/SettingsPanel'
import type { Preferences } from '../services/preferences'

type Props = {
  preferences: Preferences
  onPreferences: (next: Preferences) => void
}

export function SettingsPage(props: Props) {
  return <div className="content-scroll"><SettingsPanel {...props} /></div>
}
