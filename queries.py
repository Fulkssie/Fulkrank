QUERY_TOURNAMENT_NAME = '''
query getTournamentName($slug: String) {
  tournament(slug: $slug) {
    id
    name
    }
}
'''

QUERY_EVENT_ID = '''
query getEventId($slug: String) {
  event(slug: $slug) {
    id
    name
  }
}
'''

QUERY_EVENT = '''
query Event($eventId: ID!) {
  event(id: $eventId) {
    id
    name
    phases {
      id
      name
      phaseOrder
    }
  }
}
'''

QUERY_INIT_PHASE = '''
query Phase($phaseId: ID!, $page: Int!, $perPage: Int!) {
  phase(id: $phaseId) {
    id
    state
    seeds(query: {page: $page, perPage: $perPage}) {
      nodes {
        id
        seedNum
        entrant {
          id
          participants {
            id
            gamerTag
          }
        }
      }
    }
  }
}
'''

QUERY_PHASES = '''
query Phase($phaseId: ID!, $page: Int!, $perPage: Int!) {
  phase(id: $phaseId) {
    id
    sets(page: $page, perPage: $perPage, sortType: STANDARD) {
      nodes {
        id
        completedAt
        slots {
          entrant {
            name
            participants {
              player {
                id
                gamerTag
              }
            }
          }
          standing {
            placement
            stats {
              score {
                value
              }
            }
          }
        }
      }
    }
  }
}
'''