using Otthonra.Api;
using Xunit;

namespace Otthonra.Tests;

public class ConcurrentRefundCatchUpTests
{
    [Fact]
    public async Task ParallelOwnerReadsShareOnePassAndTheNextReadAlwaysRunsAgain()
    {
        var catchUp = new ConcurrentRefundCatchUp(); var owner = Guid.NewGuid(); var calls = 0;
        var completion = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);
        Task<int> Work() { Interlocked.Increment(ref calls); return completion.Task; }
        var readers = Enumerable.Range(0, 20).Select(_ => catchUp.RunAsync(owner, Work)).ToArray();
        Assert.Equal(1, calls); Assert.All(readers, task => Assert.False(task.IsCompleted));
        completion.SetResult(7); Assert.All(await Task.WhenAll(readers), result => Assert.Equal(7, result));
        Assert.Equal(9, await catchUp.RunAsync(owner, () => { calls++; return Task.FromResult(9); }));
        Assert.Equal(2, calls); // No completed-result/TTL cache can hide newly due refunds.
    }

    [Fact]
    public async Task DifferentOwnersDoNotBlockEachOtherAndFailuresAreNotCached()
    {
        var catchUp = new ConcurrentRefundCatchUp(); var owner = Guid.NewGuid();
        var completion = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);
        var waiting = catchUp.RunAsync(owner, () => completion.Task);
        Assert.Equal(2, await catchUp.RunAsync(Guid.NewGuid(), () => Task.FromResult(2)));
        completion.SetException(new InvalidOperationException("retryable database failure"));
        await Assert.ThrowsAsync<InvalidOperationException>(() => waiting);
        Assert.Equal(3, await catchUp.RunAsync(owner, () => Task.FromResult(3)));
        await Assert.ThrowsAsync<InvalidOperationException>(() => catchUp.RunAsync(owner, () => throw new InvalidOperationException()));
        Assert.Equal(4, await catchUp.RunAsync(owner, () => Task.FromResult(4)));
    }

    [Fact]
    public async Task AnAbortedHttpWaitDoesNotCancelOtherReadersOrRetainTheCompletedEntry()
    {
        var catchUp = new ConcurrentRefundCatchUp(); var owner = Guid.NewGuid(); var calls = 0;
        var completion = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);
        Task<int> Work() { calls++; return completion.Task; }
        using var aborted = new CancellationTokenSource();
        var first = catchUp.RunAsync(owner, Work, aborted.Token);
        var second = catchUp.RunAsync(owner, Work);
        aborted.Cancel(); await Assert.ThrowsAnyAsync<OperationCanceledException>(() => first);
        Assert.False(second.IsCompleted); Assert.Equal(1, calls);
        completion.SetResult(5); Assert.Equal(5, await second);
        Assert.Equal(6, await catchUp.RunAsync(owner, () => Task.FromResult(6)));
        using var alreadyAborted = new CancellationTokenSource(); alreadyAborted.Cancel();
        Assert.ThrowsAny<OperationCanceledException>(() => catchUp.RunAsync(owner, () => { calls++; return Task.FromResult(0); }, alreadyAborted.Token));
        Assert.Equal(1, calls);
    }
}
