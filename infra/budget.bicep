// Subscription-scope budget with real alert thresholds (T35) -- closes the gap CLAUDE.md's own
// Environment section names: "No budget alerts are configured -- spend is checked manually via
// /costs". Kept in its own file/targetScope rather than folded into main.bicep: budgets are a
// subscription-scope resource, main.bicep is entirely resource-group scope, and splitting one
// resource out is simpler than mixing scopes in one template.
targetScope = 'subscription'

@description('Email to notify at each threshold.')
param alertEmail string

@description('Monthly budget amount in USD.')
param monthlyAmountUsd int = 50

// utcNow() is only allowed in a parameter's default value, not directly inside a resource --
// hence the indirection through this parameter rather than inlining it below.
param startDate string = '${utcNow('yyyy-MM')}-01'

resource budget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: 'sbites-cloud-monthly'
  properties: {
    category: 'Cost'
    amount: monthlyAmountUsd
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: startDate
    }
    notifications: {
      actual_50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        contactEmails: [alertEmail]
        thresholdType: 'Actual'
      }
      actual_80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        contactEmails: [alertEmail]
        thresholdType: 'Actual'
      }
      actual_100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        contactEmails: [alertEmail]
        thresholdType: 'Actual'
      }
    }
  }
}
