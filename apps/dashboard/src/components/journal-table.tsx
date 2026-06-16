import {
  JournalRecord
} from "@/types/dashboard"

interface Props {
  rows: JournalRecord[]
}

export default function JournalTable(
  { rows }: Props
) {

  return (
    <table className="w-full border">

      <thead>

        <tr>

          <th>Symbol</th>

          <th>Score</th>

          <th>Decision</th>

          <th>Risk</th>

          <th>Execution</th>

        </tr>

      </thead>

      <tbody>

        {
          rows.map(
            (
              row,
              index
            ) => (

              <tr
                key={index}
              >

                <td>
                  {row.symbol}
                </td>

                <td>
                  {row.score?.score}
                </td>

                <td>
                  {
                    row.decision
                      ?.decision
                  }
                </td>

                <td>
                  {
                    row.risk
                      ?.approved
                        ? "APPROVED"
                        : "REJECTED"
                  }
                </td>

                <td>
                  {
                    row.execution
                      ?.executed
                        ? "EXECUTED"
                        : "-"
                  }
                </td>

              </tr>
            )
          )
        }

      </tbody>

    </table>
  )
}