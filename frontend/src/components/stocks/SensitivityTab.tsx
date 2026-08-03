import type { StockModel } from '../../api/types'
import { computeDcf, computeSensitivityGrid } from '../../utils/dcf'
import SensitivityTable from './SensitivityTable'
import ValuationBridgeCard from './ValuationBridgeCard'

export default function SensitivityTab({ model }: { model: StockModel }) {
  const dcf = computeDcf(model)
  const grid = computeSensitivityGrid(model)

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <SensitivityTable grid={grid} waccPercent={model.waccPercent} terminalGrowthPercent={model.terminalGrowthPercent} />
      <ValuationBridgeCard dcf={dcf} />
    </div>
  )
}
