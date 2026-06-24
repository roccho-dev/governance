package adr

#Decision: {
  id: string
  uri: string
  ts: string
  status: "Accepted" | "Deprecated"
  spec?: _
  evidence?: [...string]
  meta?: [string]: string | number | bool
}
