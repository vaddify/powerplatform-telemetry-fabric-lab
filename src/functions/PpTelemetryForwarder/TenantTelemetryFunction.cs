using Microsoft.Azure.Functions.Worker;
using Microsoft.Extensions.Logging;

namespace PpTelemetryForwarder;

public class TenantTelemetryFunction
{
    private readonly BapClient _bap;
    private readonly EventHubPublisher _publisher;
    private readonly ILogger<TenantTelemetryFunction> _log;

    public TenantTelemetryFunction(BapClient bap, EventHubPublisher publisher, ILogger<TenantTelemetryFunction> log)
    {
        _bap = bap;
        _publisher = publisher;
        _log = log;
    }

    // Every 15 minutes
    [Function(nameof(PollLicenseUsage))]
    public async Task PollLicenseUsage(
        [TimerTrigger("0 */15 * * * *")] TimerInfo timer,
        CancellationToken ct)
    {
        _log.LogInformation("Polling tenant license usage");
        var data = await _bap.GetTenantLicenseUsageAsync(ct);
        await _publisher.PublishAsync("pp.tenant.licenseUsage", data, ct);
    }

    // Every hour, look back 70 minutes for safety overlap
    [Function(nameof(PollEnvironmentLifecycle))]
    public async Task PollEnvironmentLifecycle(
        [TimerTrigger("0 0 * * * *")] TimerInfo timer,
        CancellationToken ct)
    {
        var since = DateTimeOffset.UtcNow.AddMinutes(-70);
        _log.LogInformation("Polling environment lifecycle events since {since}", since);
        var data = await _bap.GetEnvironmentLifecycleEventsAsync(since, ct);
        await _publisher.PublishAsync("pp.environment.lifecycle", data, ct);
    }
}
