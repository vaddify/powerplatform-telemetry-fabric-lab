using System.Text.Json;
using Azure.Identity;
using Azure.Messaging.EventHubs;
using Azure.Messaging.EventHubs.Producer;

namespace PpTelemetryForwarder;

public sealed class EventHubPublisher : IAsyncDisposable
{
    private readonly EventHubProducerClient _producer;

    public EventHubPublisher()
    {
        var connectionString = Environment.GetEnvironmentVariable("EVENTHUB_CONNECTION_STRING");
        if (!string.IsNullOrEmpty(connectionString))
        {
            _producer = new EventHubProducerClient(connectionString);
            return;
        }

        var fqdn = Environment.GetEnvironmentVariable("EVENTHUB_FQDN")
            ?? throw new InvalidOperationException("EVENTHUB_FQDN or EVENTHUB_CONNECTION_STRING required");
        var hub = Environment.GetEnvironmentVariable("EVENTHUB_NAME")
            ?? throw new InvalidOperationException("EVENTHUB_NAME missing");
        var clientId = Environment.GetEnvironmentVariable("UAMI_CLIENT_ID");

        var credential = string.IsNullOrEmpty(clientId)
            ? (Azure.Core.TokenCredential)new DefaultAzureCredential()
            : new ManagedIdentityCredential(clientId);

        _producer = new EventHubProducerClient(fqdn, hub, credential);
    }

    public async Task PublishAsync<T>(string eventType, T payload, CancellationToken ct)
    {
        var envelope = new
        {
            eventType,
            timestamp = DateTimeOffset.UtcNow,
            data = payload
        };
        var bytes = JsonSerializer.SerializeToUtf8Bytes(envelope);
        using var batch = await _producer.CreateBatchAsync(ct);
        if (!batch.TryAdd(new EventData(bytes)))
        {
            throw new InvalidOperationException("Event too large for batch");
        }
        await _producer.SendAsync(batch, ct);
    }

    public ValueTask DisposeAsync() => _producer.DisposeAsync();
}
